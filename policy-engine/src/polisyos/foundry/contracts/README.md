# Contracts (`polisyos.foundry.contracts`)

`polisyos.foundry.contracts` defines the shared runtime state, patch, and
fidelity contracts used by Foundry execution, calibration, and contract-aware
agent simulation.

- Last updated: 2026-04-17

## Purpose

Use this package as the common boundary for code that needs to agree on what
runtime state looks like and how mechanisms describe fidelity and patch output.
It is the stable contract layer beneath compile/execute helpers and contract-
aware simulation adapters.

## Where to Start

- [state.py](state.py) for `GlobalState`, agent/firm/market arrays, multiscale
  cells, and runtime-only simulation substate.

- [mechanism.py](mechanism.py) for patch-oriented `Mechanism`,
  `ComplexMechanism`, `PatchRecord`, and `PatchMap`.

- [fidelity.py](fidelity.py) for runtime fidelity levels.
- [../layout.py](../layout.py) for slot-to-state-path materialization that
  targets these contracts.

- [../executor.py](../executor.py) for snapshot and state-delta helpers that
  apply these contracts at runtime.

## Public Entrypoints

| Entrypoint                 | Description                                                 |
| -------------------------- | ----------------------------------------------------------- |
| `AgentState`               | Household/agent state arrays used by runtime execution.     |
| `FirmState`                | Firm production and finance arrays.                         |
| `MarketState`              | Aggregate market tensors.                                   |
| `CellState`                | Regional/sectoral aggregate state.                          |
| `HouseholdCellState`       | Household-cell welfare aggregates.                          |
| `ProcurementGraphState`    | Procurement graph runtime tensors.                          |
| `AgentSimRuntimeState`     | RNG and runtime-only distribution/network state.            |
| `GlobalState`              | Top-level compile/execute state contract.                   |
| `Mechanism`                | Patch-first mechanism contract.                             |
| `ComplexMechanism`         | Marker for complex mechanisms that still emit patches only. |
| `PatchRecord` / `PatchMap` | Patch payload structures used by merge/runtime helpers.     |
| `FidelityLevel`            | Runtime fidelity enum.                                      |

## Depends On / Depended On By

- Depends on: JAX/chex/equinox runtime libraries and
  `polisyos.foundry.agent_sim.distributions` for the embedded
  `DistributionState`.

- Depended on by: Foundry executor and registry layers, runtime mechanisms,
  calibration pure-executor flows, agent-sim wiring, quickstart, and
  release-acceptance paths.

## Common Commands

Smoke-tested on 2026-04-17:

```bash
uv run python - <<'PY'
from polisyos.foundry.contracts import FidelityLevel, GlobalState

state = GlobalState.empty(n_agents=2, n_firms=1, n_cells=1, n_household_cells=1)
print(state.agents.size, state.firms.size)
print([level.value for level in FidelityLevel])
PY
```

## Test / Verification Commands

```bash
uv run pytest tests/unit/foundry/contracts/test_state_contracts.py \
  tests/unit/foundry/contracts/test_fidelity.py -q

uv run pytest tests/unit/foundry/contracts/test_global_state.py \
  tests/unit/foundry/contracts/test_layout.py \
  tests/unit/foundry/runtime/test_executor_snapshots.py -q
```

## Reference Docs

- [docs/reference/foundry/state.md](../../../../docs/reference/foundry/state.md)
- [docs/reference/foundry/compile-execute.md](../../../../docs/reference/foundry/compile-execute.md)
- [docs/reference/foundry/agent-sim.md](../../../../docs/reference/foundry/agent-sim.md)
- [../README.md](../README.md)
