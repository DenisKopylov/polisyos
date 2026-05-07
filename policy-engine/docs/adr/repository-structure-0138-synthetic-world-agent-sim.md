# ADR-RSR-0138: Synthetic World and Agent Sim Merge Direction

## Status

Accepted

## Date

2026-05-03

## Context

`synthetic_world/` and `foundry/agent_sim/` overlap semantically around
world generation, simulation, evaluators, distributions, mechanisms, and
execution.

Phase 3B chose one canonical ownership direction before Phase 4A moved files.
Foundry already owns the low-level ABM/RL runtime, and the Foundry-owned target
removes the boundary smell from first-party `polisyos.synthetic_world` imports.

## Decision

1. Use Option A from the remediation plan.
2. `src/polisyos/synthetic_world` migrates to
   `src/polisyos/foundry/agent_sim/world` in Phase 4A.
3. The canonical target FQN is `polisyos.foundry.agent_sim.world`.
4. The top-level `polisyos.synthetic_world` facade remains wrapper-only until
   2026-10-01 and is removed after sunset.
5. `polisyos.foundry.agent_sim` remains the ABM/RL runtime facade. The moved
   world-generation surface is addressable through
   `polisyos.foundry.agent_sim.world`.
6. The repository must not keep two packages with the same simulation/world
   responsibility after Phase 4A.

## Consequences

Imports and documentation converge on Foundry as the domain owner for agent
simulation and truth-centric synthetic worlds. Static first-party imports from
`polisyos.synthetic_world.*` move to
`polisyos.foundry.agent_sim.world.*`. The non-canonical top-level path becomes
a shim with sunset.

Phase 3.4 keeps only the root facade smoke contract under
`tests/unit/synthetic_world/`; behavior coverage lives under
`tests/unit/foundry/agent_sim/world/`.

## Concrete Impact

- Blueprint:
  `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md#synthetic_world-into-foundryagentsimworld`.
- Shim id: `synthetic-world-to-agent-sim-world`.
- Source: `src/polisyos/synthetic_world/**`, `src/polisyos/foundry/agent_sim/**`.
- Owner: `team-foundry`.
- Target phases: `3B`, `4A`.
- Rollback: revert the Phase 4A move and restore shim registration.

## Related Decisions

- Related: ADR-RSR-0134 Cross-Package Shared Name Registry.
